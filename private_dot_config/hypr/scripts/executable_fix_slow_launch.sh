#!/bin/bash

sleep 1
killall xdg-desktop-portal-wlr-hyprland
killall xdg-desktop-portal-wlr
killall xdg-desktop-portal
/usr/libexec/xdg-desktop-portal-wlr-hyprland &
sleep 2
/usr/lib/xdg-desktop-portal &
