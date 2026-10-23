"""Remove the public tunnel route and point the hostname at the private edge."""
import os,json,urllib.request
base='https://api.cloudflare.com/client/v4/'
headers={'Authorization':'Bearer '+os.environ['CLOUDFLARE_API_TOKEN'],'Content-Type':'application/json'}
def api(path,data=None,method=None):
 request=urllib.request.Request(base+path,headers=headers,data=None if data is None else json.dumps(data).encode(),method=method)
 with urllib.request.urlopen(request,timeout=30) as r: body=json.load(r)
 if not body.get('success'):raise RuntimeError('Cloudflare operation failed')
 return body['result']
zone='zones/17e713ce3144867ea2d957a801739e6b'
tunnel='accounts/eb8bdd2a48912e7e45509eff79ff5473/cfd_tunnel/16198162-841c-4a9c-af9e-5c5133e06ed0/configurations'
host='builds.navonsimon.com'
config=api(tunnel)['config']
config['ingress']=[r for r in config['ingress'] if r.get('hostname')!=host]
api(tunnel,{'config':config},'PUT')
records=api(zone+'/dns_records?name='+host)
assert len(records)==1,'Review unexpected DNS records before proceeding'
api(zone+'/dns_records/'+records[0]['id'],{'type':'A','name':host,'content':'100.66.219.81','proxied':False,'ttl':60},'PUT')
# Cache purge may require a distinct permission from DNS/tunnel administration.
purge_headers={'X-Auth-Key':os.environ['CLOUDFLARE_API_KEY'],'X-Auth-Email':os.environ['CLOUDFLARE_EMAIL'],'Content-Type':'application/json'}
request=urllib.request.Request(base+zone+'/purge_cache',headers=purge_headers,data=json.dumps({'files':['https://'+host+'/','http://'+host+'/']}).encode(),method='POST')
with urllib.request.urlopen(request,timeout=30) as r: assert json.load(r)['success']
assert not any(r.get('hostname')==host for r in api(tunnel)['config']['ingress'])
record=api(zone+'/dns_records?name='+host)[0]
assert record['content']=='100.66.219.81' and not record['proxied']
print('Public tunnel route removed. DNS now points directly to the Tailscale-only HTTPS listener.')
