.PHONY: build fetch fetch-build help

# Optional plugin name passed as second positional arg
# Usage: make <target> [plugin-name]
# e.g.   make fetch-build provision
PLUGIN     := $(word 2, $(MAKECMDGOALS))
PLUGIN_ARG  = $(if $(PLUGIN),--plugin $(PLUGIN),)

## build [plugin]:       build using cached community skills
build:
	./build.py $(PLUGIN_ARG)

## fetch [plugin]:       re-download community skills only (no build)
fetch:
	./build.py --fetch-only $(PLUGIN_ARG)

## fetch-build [plugin]: re-download community skills, then build
fetch-build:
	./build.py --fetch $(PLUGIN_ARG)

## help:                 show available commands
help:
	@grep -E '^## ' Makefile | sed 's/^## /  /'

# Absorb the plugin name so Make doesn't treat it as a missing target
ifneq ($(PLUGIN),)
$(PLUGIN):
	@:
endif
