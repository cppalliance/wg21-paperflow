# Command hub. Each package owns its recipes in packages/<name>/justfile and is
# mounted here as a module, so commands read as `just <package> <verb>`, e.g.
# `just tomd score P4228R0`. Run `just --list` to see everything.

mod tomd 'packages/tomd/justfile'

# List available recipes.
default:
    @just --list
