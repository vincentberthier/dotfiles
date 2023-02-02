#!/bin/bash

sleep 10
# Handle local backups
/usr/bin/duplicacy-web -background

# Mount share space
rclone mount pcloud:home /mnt/pcloud/
