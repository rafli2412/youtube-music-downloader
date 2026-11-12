#!/bin/sh
set -eu
helper_dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
exec /bin/sh "$helper_dir/Install terminal command.command" remove "$@"
