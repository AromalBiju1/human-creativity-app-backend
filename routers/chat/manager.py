from fastapi import WebSocket
from typing import Dict,List
import json

class ConnectionManage():
    def __init__(self):
        self.active_connections: Dict[int,List[WebSocket]] = {}
        self.typing_users:Dict[int,List[int]] ={}
#connection lifecyle

    async def connect(self,websocket:WebSocket,conversation_id:int):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = []
        self.active_connections[conversation_id].append(websocket)    

    async def disconnect(self,websocket:WebSocket,conversation_id:int):
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id].remove(websocket)  
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]      


 #broadcast

    async def broadcast(self,payload:dict,conversation_id:int):
        """send a json payload to all participants in convo"""
        if conversation_id in self.active_connections:
            message =  json.dumps(payload,default=str,)
            for connection in self.active_connections[conversation_id]:
                await connection.send_text(message)


    async def broadcast_except(self,payload:dict,conversation_id:int,exclude:WebSocket):
        """broadcast to everyone except the sender"""
        if conversation_id in self.active_connections:
            message = json.dumps(payload,default=str)
            for connection in self.active_connectionsp[conversation_id]:
                if connection != exclude:
                    await connection.send_text(message)   


# typing indicators
    def set_yping(self,conversation_id:int,userid:int):
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id]= []
        if userid not in self.typing_users[conversation_id]:
            self.typing_users[conversation_id].append(userid)    



    def get_typing(self,conversation_id:int,user_id:int):
        if conversation_id in self.typing_users:
            self.typing_users[conversation_id] = [
                uid for uid in self.typing_users[conversation_id] if uid != user_id
            ]
    def get_typing_users(self,conversation_id:int)->List[int]:
        return self.typing_users.get(conversation_id,[])

        #helpers

    def is_online(self,conversation_id:int)->bool:
     """check if anyone is connected to this convo"""
     return bool[self.active_connections.get(conversation_id)]

    def online_count(self, conversation_id: int) -> int:
        return len(self.active_connections.get(conversation_id, []))


# Single shared instance — imported by the router
manager = ConnectionManager()



