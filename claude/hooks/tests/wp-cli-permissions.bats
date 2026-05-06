#!/usr/bin/env bats

HOOK="$(dirname "$BATS_TEST_FILENAME")/../wp-cli-permissions.sh"

run_hook() {
  local args="$1"
  run bash "$HOOK" <<< "$(printf '{"tool_input":{"args":"%s"}}' "$args")"
}

# -- commands that should be allowed --

@test "allows --info" {
  run_hook "--info"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows --version" {
  run_hook "--version"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows plugin list" {
  run_hook "plugin list"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows plugin list with flags" {
  run_hook "plugin list --format=json"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows option get" {
  run_hook "option get siteurl"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows user list" {
  run_hook "user list"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows transient delete update_plugins" {
  run_hook "transient delete update_plugins"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows transient delete update_themes" {
  run_hook "transient delete update_themes"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows core update" {
  run_hook "core update"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows plugin update" {
  run_hook "plugin update akismet"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

@test "allows help" {
  run_hook "help"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"permissionDecision":"allow"'* ]]
}

# -- commands that should fall through --

@test "falls through for user create" {
  run_hook "user create admin admin@example.com"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for user delete" {
  run_hook "user delete 1"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for plugin install" {
  run_hook "plugin install akismet"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for plugin delete" {
  run_hook "plugin delete akismet"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for db reset" {
  run_hook "db reset"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for db import" {
  run_hook "db import backup.sql"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for option update" {
  run_hook "option update blogname Foo"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for option delete" {
  run_hook "option delete my_option"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for post delete" {
  run_hook "post delete 1"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for transient delete arbitrary key" {
  run_hook "transient delete some_other_key"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for eval" {
  run_hook "eval 'echo 1;'"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

@test "falls through for empty args" {
  run_hook ""
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}

# -- prefix matching is prefix-only, not substring --

@test "does not allow plugin list prefixed by something else" {
  run_hook "bad plugin list"
  [ "$status" -eq 0 ]
  [ "$output" = "{}" ]
}
