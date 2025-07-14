#!/bin/bash

PROCESSOR=$(uname -m)
PROCESSOR_DIRECTORY_SUFFIX=""
if [ "$PROCESSOR" = "arm64" ]; then
    PROCESSOR_DIRECTORY_SUFFIX="-arm64"
fi
