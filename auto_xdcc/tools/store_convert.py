import json
from sys import argv

ifile = '../../xdcc_store.json'
new_ver = 3.0

def convertStore(old_ver, make_bak):
	old_dict = {}
	new_dict = {}
	with open(ifile) as f:
		old_dict = json.load(f)
		store_ver = old_dict.pop('storeVer', None)
		if store_ver and store_ver != old_ver:
			return "Version mismatch: {}".format(store_ver)
		new_dict['packlist'] = {'url':"http://arutha.info:1337/txt", 'contentLength':int(old_dict['content-length']), 'lastPack':int(old_dict['last'])}
		new_dict['timers'] = {'refresh': {'interval':900} }
		new_dict['maxConcurrentDownloads'] = 3
		new_dict['archived'] = old_dict['archived']
		new_dict['trusted'] = old_dict['trusted']
		new_dict['current'] = old_dict['current']
		new_dict['shows'] = old_dict['shows']
		new_dict['clear'] = old_dict['clear']
		new_dict['storeVer'] = new_ver

	if make_bak:
		with open('{}.v{}.bak'.format(ifile, old_ver), 'w') as f:
			json.dump(old_dict, f, indent=2)

	with open(ifile, 'w') as f:
		json.dump(new_dict, f, indent=2)

		return "Conversion from {} format to {} completed.".format(old_ver, new_ver)

if __name__ == '__main__':
	# Could just do that one conversion every time since there are no other versions to convert
	if len(argv) >= 3 and argv[1] == '-v':
		make_bak = True
		try:
			if argv[3] in ['-nb','--nobackup']:
				make_bak = False
		except: pass
		if argv[2] in ['27','2.7']:
			print(convertStore('2.7', make_bak))
	elif len(argv) == 1 or (argv and argv[1] in ['-h', '--help']):
		print("Auto-XDCC store converter tool.")
		print("Usage:")
		print("\t-v {VERSION}\t(Required)\tVersion of current store to be upgraded to the new version.")
		print("\t-nb\t\t(Optional)\tDon't make backup of old store.")