#!/bin/bash
# Load every installed indie-marketplace plugin's .env into the environment.
#
# Each plugin keeps its own .env next to its .env.example, and every declared
# variable carries its plugin's prefix (build.py enforces that). This script is
# the runtime backstop: all those files resolve into one process environment,
# so if two plugins do declare the same bare name, the second would silently
# win. Instead every file is scanned first and nothing is loaded until they all
# agree.
#
#   . load-env.sh    source it to keep the variables in your shell
#   ./load-env.sh    run it to check for collisions without keeping anything
#
# Exits 0 when everything loads clean (including when no plugin ships a .env),
# non-zero on a collision or on a .env that fails to load.
#
# Known limitation: a value spanning multiple lines (a PEM block, say) is read
# as if each of its lines declared a variable, which can report a collision
# that isn't one. Keep .env values on one line.

__LOAD_ENV_MARKETPLACE=indie-marketplace

# Bare variable names assigned in a .env file, in order. Comments and blank
# lines can't match — the name has to be the first thing on the line.
__env_keys() {
    sed -n 's/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}\([A-Za-z_][A-Za-z0-9_]*\)=.*/\2/p' "$1"
}

# Which plugin first declared $2, per the "$1" accumulator of KEY<TAB>plugin.
__env_owner() {
    printf '%s\n' "$1" | awk -F'\t' -v k="$2" '$1 == k { print $2; exit }'
}

# Every local here is __le_-prefixed: the sourcing below runs in this same
# scope, so a plainly-named variable in someone's .env could otherwise
# overwrite this function's own bookkeeping and mask a real collision.
__load_plugin_envs() {
    local __le_list __le_plugin __le_path __le_file __le_key __le_prev
    local __le_seen __le_found __le_count __le_files __le_rc

    if ! command -v claude >/dev/null 2>&1; then
        echo "load-env: \`claude\` not found on PATH — run this from a shell where the Claude Code CLI is available." >&2
        return 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "load-env: python3 not found on PATH — needed to read \`claude plugin list --json\`." >&2
        return 1
    fi

    # pipefail so a failing `claude` isn't masked by python3 parsing its
    # (empty) output happily. Its stderr is left alone so the real reason —
    # not logged in, marketplace untrusted — reaches the user.
    __le_list=$(set -o pipefail; claude plugin list --json | python3 -c '
import json, sys
marketplace = sys.argv[1]
try:
    plugins = json.load(sys.stdin)
except ValueError:
    sys.exit("could not parse `claude plugin list --json` — the CLI output format may have changed.")
if not isinstance(plugins, list):
    sys.exit("expected a list from `claude plugin list --json` — the CLI output format may have changed.")
suffix = "@" + marketplace
for p in plugins:
    if not p.get("enabled", True):
        continue
    pid = p.get("id", "")
    path = p.get("installPath")
    if path and pid.endswith(suffix):
        print(pid[: -len(suffix)] + "\t" + path)
' "$__LOAD_ENV_MARKETPLACE")
    if [ $? -ne 0 ]; then
        echo "load-env: could not enumerate installed plugins." >&2
        return 1
    fi
    if [ -z "$__le_list" ]; then
        echo "load-env: no $__LOAD_ENV_MARKETPLACE plugin is installed — nothing to load."
        return 0
    fi

    # Pass 1 — collect every .env and check the whole set for collisions.
    # Nothing is sourced yet, so a rejected run leaves the environment as it
    # was rather than half-loaded.
    __le_seen=""
    __le_found=""
    __le_count=0
    __le_files=0

    while IFS=$'\t' read -r __le_plugin __le_path; do
        [ -n "$__le_plugin" ] || continue
        __le_file="$__le_path/.env"
        [ -f "$__le_file" ] || continue
        __le_files=$((__le_files + 1))
        __le_found=$(printf '%s\n%s\t%s' "$__le_found" "$__le_plugin" "$__le_file")

        for __le_key in $(__env_keys "$__le_file"); do
            __le_prev=$(__env_owner "$__le_seen" "$__le_key")
            if [ -n "$__le_prev" ] && [ "$__le_prev" != "$__le_plugin" ]; then
                echo "load-env: refusing to load — plugins '$__le_prev' and '$__le_plugin' both declare \$$__le_key." >&2
                echo "load-env: second declaration is in $__le_file" >&2
                echo "load-env: rename it so each name carries its own plugin's prefix. Nothing was loaded." >&2
                return 1
            fi
            __le_seen=$(printf '%s\n%s\t%s' "$__le_seen" "$__le_key" "$__le_plugin")
            __le_count=$((__le_count + 1))
        done
    done <<< "$__le_list"

    if [ "$__le_files" -eq 0 ]; then
        echo "load-env: no installed $__LOAD_ENV_MARKETPLACE plugin has a .env file — nothing to load."
        return 0
    fi

    # Pass 2 — the set is clean, so load it. </dev/null keeps a .env that
    # reads stdin from swallowing the loop's own input.
    while IFS=$'\t' read -r __le_plugin __le_file; do
        [ -n "$__le_plugin" ] || continue
        set -a
        . "$__le_file" </dev/null
        __le_rc=$?
        set +a
        if [ $__le_rc -ne 0 ]; then
            echo "load-env: $__le_file failed to load (exit $__le_rc) — the environment is now incomplete." >&2
            return 1
        fi
    done <<< "$__le_found"

    echo "load-env: loaded $__le_count variable(s) from $__le_files plugin .env file(s), no collisions."
    return 0
}

__load_plugin_envs
__load_env_rc=$?
unset -f __load_plugin_envs __env_keys __env_owner
unset __LOAD_ENV_MARKETPLACE

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
    return $__load_env_rc
fi
exit $__load_env_rc
