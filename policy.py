import re
from socket import getfqdn

class PolicyMixin:
    def __init__(self, default_policy = "allow"):
        self.policies = [(".*", default_policy)]

    def add_policy(self, regexp, policy = "allow"):
        """Adds a policy for a specific host. The fqdn of the local host will
be checked against the regexp here provided"""
        self.policies.append((regexp, policy))

        return self

    def check_policy(self, hostname = getfqdn()):
        """In order, that you can't clone your big pr0n git into
your working directory you can define a policy for this repository, 
that it is only visible on your local machine."""
        result = False
        for (regexp, policy) in self.policies:
            if re.match(".*" + regexp, hostname) != None:
                if policy == "allow":
                    result = True
                else:
                    result = False

        return result

    def policy_serialize(self):
        ret = ""
        for (regexp, policy) in self.policies[1:]:
            ret += ".add_policy('%s', '%s')" %(regexp.replace("'", "\\'"),
                                               policy.replace("'", "\\'"))
        return ret
        
