#!/usr/bin/env bash
jq -r '.cwd // empty' | xargs basename 2>/dev/null
