"""Real loopback transport only exposes native exports in a desktop instance."""
import base64
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
import server

class NativeSaveHTTP(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.http=server.create_server(0,Path(self.folder.name))
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True)
        self.thread.start();self.origin=f'http://127.0.0.1:{self.http.server_port}'
        self.calls=[]
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.folder.cleanup()
    def request(self,payload,origin=None,path='/api/native-save',content_type='application/json'):
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        connection.request('POST',path,json.dumps(payload),{'Origin':self.origin if origin is None else origin,'Content-Type':content_type})
        response=connection.getresponse();status=response.status;result=json.loads(response.read());connection.close()
        return status,result
    def callback(self,*args):
        self.calls.append(args);return {'saved':True,'bytes':len(base64.b64decode(args[2]))}
    def test_ordinary_server_has_no_native_save_capability(self):
        self.assertEqual(self.request(dict(filename='owned',mime='text/plain',base64='eA=='))[0],404)
    def test_actual_local_payload_and_cancel_result(self):
        self.http.desktop_export=self.callback
        status,result=self.request(dict(filename='owned.taxbin',mime='application/octet-stream',base64='AP8='))
        self.assertEqual((status,result['bytes']),(200,2));self.assertEqual(self.calls,[('owned.taxbin','application/octet-stream','AP8=')])
        self.http.desktop_export=lambda *args:dict(cancelled=True,saved=False)
        self.assertEqual(self.request(dict(filename='owned',mime='text/plain',base64='eA==')),(200,dict(cancelled=True,saved=False)))
    def test_foreign_origin_or_non_JSON_cannot_invoke_native_picker(self):
        self.http.desktop_export=self.callback
        request=dict(filename='owned',mime='text/plain',base64='eA==')
        for options in (dict(origin='https://foreign.invalid'),dict(origin=''),dict(content_type='text/plain')):
            with self.subTest(options=options):self.assertEqual(self.request(request,**options)[0],400)
        self.assertFalse(self.calls)
    def test_exact_request_keys_before_native_callback(self):
        self.http.desktop_export=self.callback
        self.assertEqual(self.request(dict(filename='owned',path='/arbitrary/location'))[0],400)
        self.assertFalse(self.calls)
    def test_export_budget_does_not_expand_return_save_limit(self):
        self.http.desktop_export=self.callback
        request=dict(filename='large-owned.taxbin',mime='application/octet-stream',base64=base64.b64encode(b'x'*2_100_000).decode())
        self.assertEqual(self.request(request)[0],200)
        # The ordinary endpoint rejects Content-Length before reading a body.
        # Send only its declared length to avoid a client BrokenPipe racing
        # the intentional early400 while uploading several megabytes.
        connection=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        connection.putrequest('POST','/api/returns')
        connection.putheader('Origin',self.origin)
        connection.putheader('Content-Type','application/json')
        connection.putheader('Content-Length',str(len(json.dumps(request))))
        connection.endheaders();response=connection.getresponse()
        self.assertEqual(response.status,400);response.read();connection.close()
        self.assertEqual(len(self.calls),1)

if __name__=='__main__':unittest.main()
