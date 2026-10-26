# Generated protobuf definitions for Muse.ai Noise Transport & Envelope protocols

import base64
from google.protobuf import descriptor_pb2, descriptor_pool
from google.protobuf.message_factory import GetMessageClass
from client.proto._descriptors import DESC_TRANSPORT, DESC_ENVELOPE

_pool = descriptor_pool.Default()
_fd_transport = descriptor_pb2.FileDescriptorProto.FromString(base64.b64decode(DESC_TRANSPORT))
_fd_envelope = descriptor_pb2.FileDescriptorProto.FromString(base64.b64decode(DESC_ENVELOPE))

try:
    _pool.Add(_fd_transport)
except Exception:
    pass

try:
    _pool.Add(_fd_envelope)
except Exception:
    pass

NoiseTransportFrame = GetMessageClass(_pool.FindMessageTypeByName("ingress_rev_proxy.NoiseTransportFrame"))
ServiceRequest = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.ServiceRequest"))
ServiceResponse = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.ServiceResponse"))
ServiceFrame = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.ServiceFrame"))
Header = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.Header"))
ApplicationRequest = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.ApplicationRequest"))
ApplicationResponse = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.ApplicationResponse"))
BodyChunk = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.BodyChunk"))
Reset = GetMessageClass(_pool.FindMessageTypeByName("hatch.noise.Reset"))

# ServiceType enum
SERVICE_DAEMON = 0
SERVICE_SENTINEL = 1
SERVICE_VAULT = 2
SERVICE_AUTHD = 3
