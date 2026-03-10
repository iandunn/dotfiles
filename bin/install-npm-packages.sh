#!/bin/bash

source ~/dotfiles/bash/functions.sh

section "Installing npm packages"

packages=(
  vip
)

for package in "${packages[@]}"; do
  npm install -g "$package"
done

printf "\n\n✅ Done"
