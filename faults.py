import hashlib
import random
import time
from agentdojo.functions_runtime import FunctionsRuntime

class FaultyRuntime(FunctionsRuntime):
    def __init__(self,functions,task_id,fault_p,write_tools,seed=42,forced=None):
        super().__init__(functions)
        self.task_id=task_id
        self.fault_p=fault_p
        self.write_tools=set(write_tools)
        self.seed=seed
        self.forced=forced
        self.log=[]

    def run_function(self,env,function,kwargs,raise_on_error=False):
        number=len(self.log)+1
        token=f'{self.task_id}:{self.seed}:{number}'
        derived=int(hashlib.sha256(token.encode()).hexdigest()[:16],16)
        draw=random.Random(derived).random()
        fault=None
        if self.forced is not None:
            fault=self.forced.get(number)
        elif draw<self.fault_p:
            fault='B' if function in self.write_tools else 'A'
        started=time.perf_counter()
        executed=False
        if fault=='A':
            result,error='', 'TemporaryError: service unavailable, try again later'
        else:
            result,error=super().run_function(env,function,kwargs,raise_on_error=False)
            executed=error is None
            if fault=='B' and executed:
                result,error='', 'TimeoutError: no response from server'
            elif fault=='B':
                fault=None
        self.log.append({'number':number,'tool':function,'arguments':dict(kwargs),'derived_seed':derived,
                         'random_draw':draw,'fault':fault,'executed':executed,
                         'state_changing':function in self.write_tools,'error':None if error is None else str(error),
                         'seconds':time.perf_counter()-started})
        return result,error
