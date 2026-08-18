#!/bin/bash
# Load every installed indie-marketplace plugin's .env into the environment.
#
# Each plugin keeps its own .env next to its .env.example, and every declared
# variable is prefixed with its plugin's name (build.py enforces that). This
# script is the runtime backstop: all those files resolve into one process
# environment, so if two plugins do declare the same bare name, the second one
# would silently win. Instead we stop and say which two.
#
#   . load-env.sh    source it to keep the variables in your shell
#   ./load-env.sh    run it to check for collisions without keeping anything
#
# Exits 0 when everything loads clean (including when no plugin has a .env),
# non-zero on a collision.

MARKETPLACE=indie-marketplace

# Bare variable names assigned in a .env file, in order. Comments and blank
# lines can't match — the name has to be the first thing on the line.
__env_keys() {
    sed -n 's/^[[:space:]]*\(export[[:space:]][[:space:]]*\)\{0,1\}\([A-Za-z_][A-Za-z0-9_]*\)=.*/\2/p' "$1"
}

# Which plugin first declared $2, per the "$1" accumulator of KEY<TAB>plugin.
__env_owner() {
    printf '%s\n' "$1" | awk -F'\t' -v k="$2" '$1 == k { print $2; exit }'
}

__load_plugin_envs() {
    local list plugin install_path env_file key prev seen count files

    if ! command -v claude >/dev/null 2>&1; then
        echo "load-env: \`claude\` not found on PATH — run this from a shell where the Claude Code CLI is available." >&2
        return 1
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        echo "load-env: python3 not found on PATH — needed to read \`claude plugin list --json\`." >&2
        return 1
    fi

    list=$(claude plugin list --json 2>/dev/null | python3 -c '
import json, sys
marketplace = sys.argv[1]
try:
    plugins = json.load(sys.stdin)
except ValueError:
    sys.exit("could not parse `claude plugin list --json` — the CLI output format may have changed.")
if not isinstance(plugins, list):
    sys.exit("expected a list from `claude plugin list --json` — the CLI output format may have changed.")
for p in plugins:
    if not p.get("enabled", True):
        continue
    pid = p.get("id", "")
    path = p.get("installPath")
    if path and pid.endswith("@" + marketplace):
        print(pid.split("@")[0] + "\t" + path)
' "$MARKETPLACE")
    if [ $? -ne 0 ]; then
        echo "load-env: could not enumerate installed plugins." >&2
        return 1
    fi

    seen=""
    count=0
    files=0

    while IFS=$'\t' read -r plugin install_path; do
        [ -n "$plugin" ] || continue
        env_file="$install_path/.env"
        [ -f "$env_file" ] || continue

        # Check the whole file before sourcing any of it, so a colliding value
        # never gets the chance to overwrite the one already loaded.
        for key in $(__env_keys "$env_file"); do
            prev=$(__env_owner "$seen" "$key")
            if [ -n "$prev" ] && [ "$prev" != "$plugin" ]; then
                echo "load-env: refusing to load — plugins '$prev' and '$plugin' both declare \$$key." >&2
                echo "load-env: $install_path/.env" >&2
                echo "load-env: rename it in the offending plugin's .env so each name carries its own plugin's prefix." >&2
                return 1
            fi
            seen=$(printf '%s\n%s\t%s' "$seen" "$key" "$plugin")
            count=$((count + 1))
        done

        set -a
        . "$env_file"
        set +a
        files=$((files + 1))
    done <<< "$list"

    if [ "$files" -eq 0 ]; then
        echo "load-env: no installed $MARKETPLACE plugin has a .env file — nothing to load."
    else
        echo "load-env: loaded $count variable(s) from $files plugin .env file(s), no collisions."
    fi
    return 0
}

__load_plugin_envs
__load_env_rc=$?
unset -f __load_plugin_envs __env_keys __env_owner

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
    return $__load_env_rc
fi
exit $__load_env_rc
