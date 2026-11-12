#!/bin/sh
set -eu

# Optional helper. Never edits shell profiles or replaces an unrelated command.
operation=${1:-install}
app_bundle=${2:-/Applications/YouTube Music Downloader.app}
command_dir=${3:-$HOME/.local/bin}
if [ "$#" -lt 2 ] && [ ! -d "$app_bundle" ] && [ -d "$HOME/Applications/YouTube Music Downloader.app" ]; then
  app_bundle="$HOME/Applications/YouTube Music Downloader.app"
fi
case "$operation" in install|remove) ;; *) printf '%s\n' 'Use install or remove.' >&2; exit 2 ;; esac
case "$app_bundle" in /*) ;; *) printf '%s\n' 'Choose an absolute app path.' >&2; exit 2 ;; esac
case "$command_dir" in /*) ;; *) printf '%s\n' 'Choose an absolute command directory.' >&2; exit 2 ;; esac
app_command="$app_bundle/Contents/MacOS/ytmp3"
command_link="$command_dir/ytmp3"

if [ "$operation" = remove ]; then
  if [ -L "$command_link" ] && [ "$(readlink "$command_link")" = "$app_command" ]; then
    rm "$command_link"
    printf '%s\n' 'Removed the ytmp3 terminal link. The app, settings, and downloads were kept.'
  elif [ -e "$command_link" ] || [ -L "$command_link" ]; then
    printf '%s\n' 'An unrelated ytmp3 command exists; it was left untouched.' >&2
    exit 1
  else
    printf '%s\n' 'No matching terminal link is installed.'
  fi
  exit 0
fi

if [ ! -x "$app_command" ]; then
  printf '%s\n' 'Copy YouTube Music Downloader to Applications first, then run this helper again.' >&2
  exit 1
fi
mkdir -p "$command_dir"
if [ -e "$command_link" ] || [ -L "$command_link" ]; then
  if [ ! -L "$command_link" ] || [ "$(readlink "$command_link")" != "$app_command" ]; then
    printf '%s\n' 'An unrelated ytmp3 command exists; it was left untouched.' >&2
    exit 1
  fi
else
  ln -s "$app_command" "$command_link"
fi
printf 'Terminal command installed at:\n%s\n' "$command_link"
case ":$PATH:" in
  *":$command_dir:"*) printf '%s\n' 'You can now run: ytmp3 --help' ;;
  *)
    printf '%s\n' 'To use ytmp3 by name, add this directory to your shell PATH:'
    printf '%s\n' "$command_dir"
    printf '%s\n' 'For the default directory, add this line to ~/.zprofile and open a new terminal:'
    printf '%s\n' 'export PATH="$HOME/.local/bin:$PATH"'
    ;;
esac
