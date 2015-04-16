#!/bin/bash

BASE=/opt/APG
BIN=${HOME}/bin
ETC=${HOME}/etc
SERVERS=servers.xml

mkdir ${BIN} 2>/dev/null
mkdir ${ETC} 2>/dev/null

##
## Link per-achitecture scripts to servers.sh
##
for TAG in frontend primary additional collector
do
        [[ -x ${BIN}/${TAG}.sh ]] || ln ${BIN}/servers.sh ${BIN}/${TAG}.sh
done

##
## Go looking for the ${SERVERS} file.
##
cd ${BASE}/Custom/WebApps-Resources/Default
cd Default.1 2>/dev/null   # only exists in 3.5sp1
cd centralized-management
[[ -f ${SERVERS} ]] || ( echo missing ${SERVERS} file ; exit 1 )

##
##  Create a list of all servers, and per-architecture.
##
/bin/grep name= ${SERVERS} | \
        /bin/sed -e 's/^.* name=//' -e 's/ .*//' -e 's/"//g' \
        > ${ETC}/servers_all
/bin/grep name= ${SERVERS} | /bin/grep windows-x64 | \
        /bin/sed -e 's/^.* name=//' -e 's/ .*//' -e 's/"//g' \
        > ${ETC}/servers_win
/bin/grep name= ${SERVERS} | /bin/grep -v windows-x64 | \
        /bin/sed -e 's/^.* name=//' -e 's/ .*//' -e 's/"//g' \
        > ${ETC}/servers_ux

##
## Clean out any old versions.
##
cd ${ETC}
/bin/rm ./{frontend,primary,additional,collector}_{all,win,ux} 2>/dev/null

##
##  Let the user tag each server.
##
echo "For each server, enter its tag, one or more of Frontend, Primary,"
echo "Additional and/or Collector. You may enter just the initial."
for s in $(< ./servers_all )
do
        read -r -p "$s: " -a TAGS
        for TAG in ${TAGS[*]}
        do
                case $TAG in
                [Ff]*) echo $s>>./frontend_all ;;
                [Pp]*) echo $s>>./primary_all ;;
                [Aa]*) echo $s>>./additional_all ;;
                [Cc]*) echo $s>>./collector_all ;;
                esac
        done
done

##
##  Create tagged per-architecture files.
##
for TAG in frontend primary additional collector
do
        grep -f ./servers_win ./${TAG}_all >./${TAG}_win
        grep -f ./servers_ux ./${TAG}_all >./${TAG}_ux
done
