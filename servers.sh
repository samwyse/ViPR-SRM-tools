#!/bin/bash

tag=$( basename $0 .sh )
for s in $(< ${HOME}/etc/${tag}_ux )
do
        echo === $s ===
        ssh $s "${@}"
done
