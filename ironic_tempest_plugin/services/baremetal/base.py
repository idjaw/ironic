#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import functools

from oslo_serialization import jsonutils as json
import six
from six.moves.urllib import parse as urllib
from tempest.lib.common import rest_client


def handle_errors(f):
    """A decorator that allows to ignore certain types of errors."""

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        param_name = 'ignore_errors'
        ignored_errors = kwargs.get(param_name, tuple())

        if param_name in kwargs:
            del kwargs[param_name]

        try:
            return f(*args, **kwargs)
        except ignored_errors:
            # Silently ignore errors
            pass

    return wrapper


class BaremetalClient(rest_client.RestClient):
    """Base Tempest REST client for Ironic API."""

    uri_prefix = ''

    def serialize(self, object_dict):
        """Serialize an Ironic object."""

        return json.dumps(object_dict)

    def deserialize(self, object_str):
        """Deserialize an Ironic object."""

        return json.loads(object_str)

    def _get_uri(self, resource_name, uuid=None, permanent=False):
        """Get URI for a specific resource or object.

        :param resource_name: The name of the REST resource, e.g., 'nodes'.
        :param uuid: The unique identifier of an object in UUID format.
        :returns: Relative URI for the resource or object.

        """
        prefix = self.uri_prefix if not permanent else ''

        return '{pref}/{res}{uuid}'.format(pref=prefix,
                                           res=resource_name,
                                           uuid='/%s' % uuid if uuid else '')

    def _make_patch(self, allowed_attributes, **kwargs):
        """Create a JSON patch according to RFC 6902.

        :param allowed_attributes: An iterable object that contains a set of
            allowed attributes for an object.
        :param **kwargs: Attributes and new values for them.
        :returns: A JSON path that sets values of the specified attributes to
            the new ones.

        """
        def get_change(kwargs, path='/'):
            for name, value in six.iteritems(kwargs):
                if isinstance(value, dict):
                    for ch in get_change(value, path + '%s/' % name):
                        yield ch
                else:
                    if value is None:
                        yield {'path': path + name,
                               'op': 'remove'}
                    else:
                        yield {'path': path + name,
                               'value': value,
                               'op': 'replace'}

        patch = [ch for ch in get_change(kwargs)
                 if ch['path'].lstrip('/') in allowed_attributes]

        return patch

    def _list_request(self, resource, permanent=False, **kwargs):
        """Get the list of objects of the specified type.

        :param resource: The name of the REST resource, e.g., 'nodes'.
        :param **kwargs: Parameters for the request.
        :returns: A tuple with the server response and deserialized JSON list
                 of objects

        """
        uri = self._get_uri(resource, permanent=permanent)
        if kwargs:
            uri += "?%s" % urllib.urlencode(kwargs)

        resp, body = self.get(uri)
        self.expected_success(200, resp.status)

        return resp, self.deserialize(body)

    def _show_request(self, resource, uuid, permanent=False, **kwargs):
        """Gets a specific object of the specified type.

        :param uuid: Unique identifier of the object in UUID format.
        :returns: Serialized object as a dictionary.

        """
        if 'uri' in kwargs:
            uri = kwargs['uri']
        else:
            uri = self._get_uri(resource, uuid=uuid, permanent=permanent)
        resp, body = self.get(uri)
        self.expected_success(200, resp.status)

        return resp, self.deserialize(body)

    def _create_request(self, resource, object_dict):
        """Create an object of the specified type.

        :param resource: The name of the REST resource, e.g., 'nodes'.
        :param object_dict: A Python dict that represents an object of the
                            specified type.
        :returns: A tuple with the server response and the deserialized created
                 object.

        """
        body = self.serialize(object_dict)
        uri = self._get_uri(resource)

        resp, body = self.post(uri, body=body)
        self.expected_success(201, resp.status)

        return resp, self.deserialize(body)

    def _delete_request(self, resource, uuid):
        """Delete specified object.

        :param resource: The name of the REST resource, e.g., 'nodes'.
        :param uuid: The unique identifier of an object in UUID format.
        :returns: A tuple with the server response and the response body.

        """
        uri = self._get_uri(resource, uuid)

        resp, body = self.delete(uri)
        self.expected_success(204, resp.status)
        return resp, body

    def _patch_request(self, resource, uuid, patch_object):
        """Update specified object with JSON-patch.

        :param resource: The name of the REST resource, e.g., 'nodes'.
        :param uuid: The unique identifier of an object in UUID format.
        :returns: A tuple with the server response and the serialized patched
                 object.

        """
        uri = self._get_uri(resource, uuid)
        patch_body = json.dumps(patch_object)

        resp, body = self.patch(uri, body=patch_body)
        self.expected_success(200, resp.status)
        return resp, self.deserialize(body)

    @handle_errors
    def get_api_description(self):
        """Retrieves all versions of the Ironic API."""

        return self._list_request('', permanent=True)

    @handle_errors
    def get_version_description(self, version='v1'):
        """Retrieves the desctription of the API.

        :param version: The version of the API. Default: 'v1'.
        :returns: Serialized description of API resources.

        """
        return self._list_request(version, permanent=True)

    def _put_request(self, resource, put_object):
        """Update specified object with JSON-patch."""
        uri = self._get_uri(resource)
        put_body = json.dumps(put_object)

        resp, body = self.put(uri, body=put_body)
        self.expected_success([202, 204], resp.status)
        return resp, body
