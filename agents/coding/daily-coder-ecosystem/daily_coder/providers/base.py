from abc import ABC, abstractmethod
from ..models import Invocation, InvocationResult
class Provider(ABC):
    @abstractmethod
    def invoke(self,request:Invocation)->InvocationResult: ...
