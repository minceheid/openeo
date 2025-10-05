#!/usr/bin/bash

date
echo "Test output"

i=30

while [ $i -gt 0 ] ; do

	i=$(( $i - 1 ))
	echo "testing $i"
	sleep 1

done
