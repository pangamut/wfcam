#!/usr/bin/bash

MP3DIR=/etc/audioplayer/MP3

run = 1

while [ run ]
do
  for i in $MP3DIR/* 
  do
    mpg123 -q $i
  done

done
