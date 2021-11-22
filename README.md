# ViPR-SRM-tools
A collection of scripts and such that I find useful during the installation and/or upgrade of ViPR SRM.

Best practices call for using the vApp installer, so these are BASH scripts to help manage Linux environments.
I typically log into one server, install the scripts, and do everything from there.  On the other hand,
they could be re-written as Powershell to use PuTTY, and handle both Windows and Linux architectures.

## Installation
The `mk-servers.sh` script assumes that the `servers.sh` script is installed in $HOME/bin, i.e. /root/bin.
This is convenient, because (at least on a ViPR SRM appliance) $HOME/bin is already set up as part of your
path, whether the directory exists or not.  When you run the script, it will try to create $HOME/{bin,etc} 
and create links from the supported tags to the `servers.sh` file.  (Yes, that file won't be there if the
directory was just created.  I plan to fix that later by moving to a seperate installatin script.)

## Preparation
The `servers.sh` script uses SSH to connect to all of the servers in an installation.  You almost certainly
want to have SSH set up so you won't be prompted for a password at each connection attempt.  Well, a few
years ago I wrote "How to Set Up Putty for Password-Free SSH" for a client.  (Yes, it's a Word doc.  Sorry.)
Despite it's name, it also contains much information about setting up SSH.  Read it and become an expert.

## Usage
You will typically only run `mk-servers.sh` once.  It will create fifteen files containing various permutations
of the SRM servers.  These wil be named `etc/{servers,frontend,primary,additional,collector}_{all,win,ux}`.
Thereafter, you will use `servers.sh` to run a command on all Linux-based SRM servers.  You can also use 
`{frontend,primary,additional,collector}.sh` to run a command on the various subsets.  For example, if you
want to reboot all of the backend servers, in the manner suggested in the documentation, you would do this:

    additional.sh 'shutdown -r now'
    sleep 30
    primary.sh 'shutdown -r now'

Or, perhaps you want to restart the tomcat service on all of the frontend servers:

    frontend.sh manage-modules.sh service restart tomcat

You get the idea.

# To Do
- [ ] Create a real installer.
- [ ] Create a PDF version of "How to Set Up Putty for Password-Free SSH".
