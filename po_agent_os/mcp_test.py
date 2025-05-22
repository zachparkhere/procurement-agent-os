import requests

requests.post("http://localhost:8000/send", json={
    "sender": "test",
    "receiver": "external_comm_hub",
    "type": "vendor_reply",
    "content": "",
    "payload": {}
})
