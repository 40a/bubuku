import json
import logging

import boto3
import requests

from bubuku.zookeeper.exhibior import AWSExhibitorAddressProvider
from bubuku.zookeeper.exhibior import LocalAddressProvider
from bubuku.config import Config

_LOG = logging.getLogger('bubuku.amazon')


class EnvProvider(object):
    def get_own_ip(self) -> str:
        raise NotImplementedError('Not implemented')

    def get_address_provider(self, config: Config):
        raise NotImplementedError('Not implemented')

    @staticmethod
    def create_env_provider(dev_mode: bool):
        return LocalEnvProvider() if dev_mode else AmazonEnvProvider()


class AmazonEnvProvider(EnvProvider):
    NONE = object()

    def __init__(self):
        self.document = None
        self.aws_addr = '169.254.169.254'

    def _get_document(self) -> dict:
        if not self.document:
            try:
                self.document = requests.get(
                    'http://{}/latest/dynamic/instance-identity/document'.format(self.aws_addr),
                    timeout=5).json()
                _LOG.info("Amazon specific information loaded from AWS: {}".format(
                    json.dumps(self.document, indent=2)))
            except Exception as ex:
                _LOG.warn('Failed to download AWS document', exc_info=ex)
                self.document = AmazonEnvProvider.NONE
        return self.document if self.document != AmazonEnvProvider.NONE else None

    def get_aws_region(self) -> str:
        doc = self._get_document()
        return doc['region'] if doc else None

    def get_own_ip(self) -> str:
        doc = self._get_document()
        return doc['privateIp'] if doc else '127.0.0.1'

    def get_addresses_by_lb_name(self, lb_name) -> list:
        region = self.get_aws_region()

        private_ips = []

        if region is not None:
            elb = boto3.client('elb', region_name=region)
            ec2 = boto3.client('ec2', region_name=region)

            response = elb.describe_instance_health(LoadBalancerName=lb_name)

            for instance in response['InstanceStates']:
                if instance['State'] == 'InService':
                    private_ips.append(ec2.describe_instances(
                        InstanceIds=[instance['InstanceId']])['Reservations'][0]['Instances'][0]['PrivateIpAddress'])

        else:
            private_ips = [lb_name]
        _LOG.info("Ip addresses for {} are: {}".format(lb_name, private_ips))
        return private_ips

    def get_address_provider(self, config: Config):
        return AWSExhibitorAddressProvider(self, config.zk_stack_name)


class LocalEnvProvider(EnvProvider):
    def get_own_ip(self) -> str:
        return '127.0.0.1'

    def get_address_provider(self, config: Config):
        return LocalAddressProvider()
