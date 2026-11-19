import json
import time
from types import SimpleNamespace
from agentdojo.agent_pipeline.tool_execution import tool_result_to_str
from agentdojo.functions_runtime import FunctionCall
from agentdojo.types import ChatAssistantMessage,ChatToolResultMessage,text_content_block_from_string as text
from base_agent import Agent as BaseAgent,StopEpisode

class SamplingClient:
    def __init__(self,client,temperature,seed):
        self.client=client
        self.temperature=temperature
        self.seed=seed
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self,**kwargs):
        kwargs['temperature']=self.temperature
        kwargs['seed']=self.seed
        return self.client.chat.completions.create(**kwargs)
    def close(self):
        self.client.close()

class PolicyRuntime:
    def __init__(self,runtime,agent):
        self.runtime=runtime
        self.agent=agent
        self.attempts=[]
    def run_function(self,env,function,kwargs):
        for retry in range(3):
            if retry:
                if self.agent.trace['tool_calls']>=self.agent.config['max_tools']:
                    break
                self.agent.trace['tool_calls']+=1
            result,error=self.runtime.run_function(env,function,kwargs)
            output=tool_result_to_str(result) if error is None else str(error)
            self.attempts.append({'tool':function,'arguments':dict(kwargs),'output':output,'error':None if error is None else str(error)})
            self.agent.trace['runtime_log']=self.runtime.log
            self.agent.record({'kind':'runtime_attempt','attempt':dict(self.runtime.log[-1]),'output':output})
            if error is None:
                break
            if self.agent.policy=='P0':
                break
            if self.agent.policy=='P2' and function in self.runtime.write_tools:
                output=str(error)+' Action may have been executed; check state before retrying.'
                return '',output
        return result,error

class Agent(BaseAgent):
    def __init__(self,config,path,policy='P0',temperature=0,seed=42):
        super().__init__(config,'react',path)
        self.policy=policy
        self.client=SamplingClient(self.client,temperature,seed)
        self.trace.update(policy=policy,temperature=temperature,seed=seed,runtime_log=[])

    def execute(self,call,runtime,env,chat,log,allowed=None):
        controller=PolicyRuntime(runtime,self)
        before=len(log)
        super().execute(call,controller,env,chat,log,allowed)
        # AgentDojo receives every actual attempt, while the model gets one aggregate result.
        if controller.attempts:
            del log[before:]
            for number,attempt in enumerate(controller.attempts):
                call_id=call['id'] if number==0 else call['id']+f'_retry{number}'
                fc=FunctionCall(function=attempt['tool'],args=attempt['arguments'],id=call_id)
                log.extend([ChatAssistantMessage(role='assistant',content=None,tool_calls=[fc]),
                            ChatToolResultMessage(role='tool',content=[text(attempt['output'])],tool_call_id=fc.id,tool_call=fc,error=attempt['error'])])
            if len(controller.attempts)>1:
                chat[-1]['content']='Automatic attempts: '+str(len(controller.attempts))+'. Final result: '+chat[-1]['content']
