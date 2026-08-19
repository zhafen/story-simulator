#!/usr/bin/env bash
# Catches the submodule-pointer mistake from PR #36: a "bump" that's
# actually a rewind, or a pointer to a commit never pushed upstream.
#
# Usage:
#   check-submodule-pointers.sh --staged           # compare index vs HEAD
#   check-submodule-pointers.sh <old-rev> <new-rev> # compare two superproject revisions
set -euo pipefail

if [ "${1:-}" = "--staged" ]; then
  diff_args=(--cached HEAD)
else
  old_rev="${1:?usage: check-submodule-pointers.sh --staged | <old-rev> <new-rev>}"
  new_rev="${2:?usage: check-submodule-pointers.sh --staged | <old-rev> <new-rev>}"
  git fetch --quiet origin "$old_rev" "$new_rev" 2>/dev/null || true
  diff_args=("$old_rev" "$new_rev")
fi

fail=0
checked_any=0

while read -r old_mode new_mode old_sha new_sha status path; do
  old_mode=${old_mode#:}
  [ "$new_mode" = "160000" ] || continue
  [ "$old_sha" = "$new_sha" ] && continue
  checked_any=1

  if [ "$old_sha" = "0000000000000000000000000000000000000000" ]; then
    echo "New submodule $path at $new_sha - nothing to compare against, skipping."
    continue
  fi

  echo "Checking $path: $old_sha -> $new_sha"

  if [ ! -e "$path/.git" ]; then
    echo "  SKIP: $path isn't checked out here, can't verify."
    continue
  fi

  # CI (and some local clones) fetch submodules at --depth=1, which is
  # too shallow to answer ancestry questions - get enough history first.
  git -C "$path" fetch --quiet --unshallow origin 2>/dev/null \
    || git -C "$path" fetch --quiet origin 2>/dev/null || true
  git -C "$path" fetch --quiet origin '+refs/heads/*:refs/remotes/origin/*' 2>/dev/null || true

  for sha in "$old_sha" "$new_sha"; do
    git -C "$path" cat-file -e "$sha" 2>/dev/null \
      || git -C "$path" fetch --quiet origin "$sha" 2>/dev/null || true
  done

  if ! git -C "$path" cat-file -e "$new_sha" 2>/dev/null; then
    echo "  FAIL: $new_sha isn't in $path's object store, even after fetching."
    fail=1
    continue
  fi

  default_branch=$(git -C "$path" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || echo "origin/main")

  reachable_branch=""
  while IFS= read -r ref; do
    if git -C "$path" merge-base --is-ancestor "$new_sha" "$ref" 2>/dev/null; then
      reachable_branch="$ref"
      [ "$ref" = "$default_branch" ] && break
    fi
  done < <(git -C "$path" for-each-ref --format='%(refname:short)' refs/remotes/origin/)

  if [ -z "$reachable_branch" ]; then
    echo "  FAIL: $new_sha isn't reachable from any of $path's remote branches (origin/*) - has it been pushed upstream at all?"
    fail=1
    continue
  fi

  if [ "$reachable_branch" != "$default_branch" ]; then
    echo "  NOTE: reachable only via $path's '$reachable_branch', not yet merged into $default_branch -- fine for a stacked/WIP PR, remember to bump this again once '$reachable_branch' merges."
  fi

  if git -C "$path" cat-file -e "$old_sha" 2>/dev/null; then
    if git -C "$path" merge-base --is-ancestor "$new_sha" "$old_sha" 2>/dev/null; then
      echo "  FAIL: $path pointer moved BACKWARD - $new_sha is an ancestor of $old_sha, not a descendant."
      fail=1
      continue
    fi
  fi

  echo "  OK"
done < <(git diff --raw "${diff_args[@]}")

if [ "$checked_any" -eq 0 ]; then
  echo "No submodule pointer changes to check."
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "Submodule pointer check failed."
  exit 1
fi

exit 0
