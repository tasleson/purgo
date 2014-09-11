purgo
=====

Utility to dynamically reconfigure /etc/resolv.conf based on performance or
availability.

Background
---------
In August of 2014 Charter Communications suffered a DNS outage, at least from
my perspective.  I used google's public DNS services to ride out the outage and
when my dhclient refreshed my IP addresses the changes were replaced as expected
with those retrieved from the ISP.  I could of course use prepend statements
in the /etc/dhclient.conf, but I wanted something that would check what my
ISP had given me against what others were publicly available and update my
/etc/resolv.conf as needed based on lookup times and availability.
Thus this script was born.  Setup and periodically run in a cron job.

There is probably a better way to do this, but hey writing python is _fun_ 
right?

Requirements (python packages)
------------
* dnspython http://www.dnspython.org/
* yaml http://pyyaml.org/

Using
-----
Drop purgo.py and purgo.cfg on a box and run.  Use --help for options.

Theory
------
Resolv.conf can have up to three nameserver entries for which it tries one by
one waiting for a timeout.  This utility tries to ensure that those three
entries will be the best that they can be.

Warning
-------
Not heavily tested and it needs to run as root to modify /etc/resolv.conf.  Use
at your own risk!
