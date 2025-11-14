#!/usr/bin/env bash

RES=$(ping -c 1 tyrex-gl01-dev.kub.local > /dev/null 2>&1 ; echo $?)
if [[ $RES == 0 ]]; then
    echo "󱫋"
fi
