#!/bin/bash

RES=$(ping -c 1 desktop1.px.cls.fr > /dev/null 2>&1 ; echo $?)
if [[ $RES == 0 ]]; then
    echo "󱫋"
fi
