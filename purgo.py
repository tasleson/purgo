#!/usr/bin/env python2

# Copyright (C) 2014  Tony Asleson <tony DOT asleson AT gmail DOT com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import dns.resolver
import random
import string
import time
import yaml
import argparse
import sys
import os

MAXNS = 3
NUM_SAMPLES = 0
VALID_HOST = ''


class Duration(object):
    """
    Used for getting timings using the with syntax for a block
    """
    def __init__(self):
        self.start = 0
        self.end = 0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *ignore):
        self.end = time.time()

    def amount(self):
        return self.end - self.start


class ResolveConf(object):
    """
    Handles reading in and writing out /etc/resolv.conf
    """

    comment_note = '# Commented out with purgo.py'

    def __init__(self, resolve_conf='/etc/resolv.conf'):

        self._copy_paste = []
        self._commented_out_ns = []
        self._ns = []
        self._file = resolve_conf

        with open(resolve_conf) as f:
            config = f.readlines()

        for c in config:
            c = c.strip()
            if c.startswith('#') or c.startswith(';'):
                # See if we have a commented out name server
                if c.startswith('# nameserver') or \
                        c.startswith('; nameserver'):
                    ns = c[len('# nameserver '):].strip()
                    self._commented_out_ns.append(ns)
                else:
                    if c != ResolveConf.comment_note:
                        self._copy_paste.append(c)
            else:
                if c.startswith('nameserver'):
                    ns = c[len('nameserver'):].strip()
                    self._ns.append(ns)
                else:
                    self._copy_paste.append(c)

        self._commented_out_ns = list(set(self._commented_out_ns))
        self._ns = list(set(self._ns))

    def ns_get(self):
        return list(self._ns)

    def commented_out_ns_get(self):
        return list(self._commented_out_ns)

    def commented_out_ns_set(self, name_servers):
        self._commented_out_ns = list(name_servers)

    def ns_set(self, name_servers):
        self._ns = list(name_servers)

    def save(self):
        with open(self._file, 'w') as f:
            f.writelines([x + os.linesep for x in self._copy_paste])
            f.write(ResolveConf.comment_note + '\n')
            f.writelines(['# nameserver ' + x + os.linesep
                          for x in self._commented_out_ns])
            f.writelines(['nameserver ' + x + os.linesep for x in self._ns])


def random_host(l=63):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(l)) \
           + ".com"


def get_config(cfg_file):
    configuration = yaml.safe_load(open(cfg_file).read())
    if configuration is None:
        # If nothing we will try to default to some sane defaults at the time
        # of this coding.
        configuration = dict(google=['8.8.8.8', '8.8.4.4'],
                             opendns=['208.67.222.222', '208.67.220.220'])
    return configuration


def dns_lookup(dns_server, host_name):
    """
    Returns tuple (address, resolve time)
    :param dns_server:  DNS server to use
    :param host_name:   Host name to lookup
    :return: (resolved address, resolve time), None indicates did not resolve
    """
    answers = None
    m_dns = dns.resolver.Resolver()
    m_dns.nameservers = [dns_server]
    with Duration() as lookup_time:
        try:
            answers = m_dns.query(host_name, 'A')
        except Exception:
            pass

    if answers and len(answers):
        return answers[0].address, lookup_time.amount()
    return None, lookup_time.amount()


def moving_average(avg, new_sample):
    """
    Calculates a moving average
    :param avg: Current value of average
    :param new_sample: New sample
    :return: New moving average
    """
    avg -= avg / float(NUM_SAMPLES)
    avg += new_sample / float(NUM_SAMPLES)
    return avg


def check_servers(dns_servers):
    """
    Goes through the hash of servers and calculates averages for them
    :param dns_servers:
    :return: None
    """
    # Note: We walk though all the servers with each different value to space
    # out the dns queries so we don't hammer the dns server quickly
    lookup_times = {}
    host_name_exists = VALID_HOST

    for i in range(0, NUM_SAMPLES):
        host_name_missing = random_host()
        for host in [host_name_exists, host_name_missing]:
            for ip_address, meta_data in dns_servers.items():
                lookup_time = dns_lookup(ip_address, host)[1]
                meta_data['avg'] = moving_average(meta_data['avg'],
                                                  lookup_time)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Optimize /etc/resolv.conf for reliability or "
                    "lookup time.  "
                    ""
                    "This was created to fend off internet outages where "
                    "the ISP DNS server(s) get taken offline by denial of "
                    "service attacks or when they go offline for other "
                    "reasons etc.")

    parser.add_argument('-c', metavar='<config file>', type=str,
                        action='store', required=True,
                        help='Yaml file which contains DNS servers ')
    parser.add_argument('--resolv_conf', metavar='<resolv conf>', type=str,
                        action='store', default='/etc/resolv.conf',
                        help='Where to read/write resolv.conf, useful '
                             'for testing (default /etc/resolv.conf)')
    parser.add_argument('--num_samples', metavar='<num samples>', type=int,
                        action='store', default=5,
                        help='Number of times to do lookups for each '
                             'DNS server (default 5)')
    parser.add_argument('--method', metavar='<enumerated option>',
                        action='store', choices=['SPEED', 'RELIABILITY'],
                        default='RELIABILITY', help='What are you wanting '
                                                    '(default RELIABILITY)')
    parser.add_argument('--valid_host', metavar='<valid hostname to lookup',
                        action='store', default='google.com',
                        help='Valid host name to resolve (default google.com)')
    args = parser.parse_args()

    if os.path.exists(args.c):
        NUM_SAMPLES = max(args.num_samples, 1)
        VALID_HOST = args.valid_host

        all_dns_servers = {}

        resolver_config = ResolveConf(args.resolv_conf)
        cfg = get_config(args.c)

        all_dns_servers = {}

        for provider, dns_server_list in cfg.items():
            for server_ip in dns_server_list:
                all_dns_servers[server_ip] = dict(provider=provider, avg=0.0)

        starting_name_servers = resolver_config.ns_get()
        all_resolv_conf = resolver_config.ns_get()
        all_resolv_conf.extend(resolver_config.commented_out_ns_get())

        for name_server in all_resolv_conf:
            if name_server not in all_dns_servers:
                all_dns_servers[name_server] = dict(provider='isp', avg=0.0)

        check_servers(all_dns_servers)

        # Get sorted list of IP by avg lookup time
        sorted_ip = sorted(all_dns_servers, key=lambda key:
                            all_dns_servers[key]['avg'])

        # Get ISP dns list to store in commented out section
        isp_ns = [k for k, v in all_dns_servers.items()
                  if v['provider'] == 'isp']

        if args.method == 'SPEED':
            # Pick fastest first three and go with it.
            resolver_config.ns_set(sorted_ip[:MAXNS])
        else:
            # Pick fastest from each different provider, sorted by performance
            # This hopefully provides more redundancy.
            fastest_each_group = []
            already_picked = {}

            # Probably a more pythonic way to do the following
            for ip in sorted_ip:
                server_data = all_dns_servers[ip]
                if server_data['provider'] not in already_picked:
                    already_picked[server_data['provider']] = None
                    fastest_each_group.append(ip)
                    if len(fastest_each_group) == MAXNS:
                        break

            resolver_config.ns_set(fastest_each_group)

        # Build the appropriate entries and write out the resolv.conf file
        resolver_config.commented_out_ns_set(isp_ns)

        # Don't write out file if nothing has changed
        if starting_name_servers != resolver_config.ns_get():
            resolver_config.save()
    else:
        sys.stderr.write("Config file '%s' not found!\n" % (args.c))
        sys.exit(1)
    sys.exit(0)