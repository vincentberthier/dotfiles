#!/bin/bash

daemon=$(pidof spotifyd)
if [[ -z $daemon ]]; then spotifyd; fi

spt
