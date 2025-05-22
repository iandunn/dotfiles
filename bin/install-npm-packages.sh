#!/bin/bash

packages=(
  vip
)

for package in "${packages[@]}"; do
  npm install -g "$package"
done

printf "\nnpm packages installed.\n"
