#!/usr/bin/env python3
"""Build a development-signed offline APK with an already-installed Android SDK.

No SDK/license install, real-device installation, accounts or remote services.
The private development keystore is stored in the caller-selected work directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def run(args,**kwargs):
    subprocess.run([str(x) for x in args],check=True,**kwargs)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sdk',type=Path,required=True)
    parser.add_argument('--java-home',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist')
    parser.add_argument('--signing-keystore',type=Path,help='Existing private development keystore; keep this identity when updating an installed preview')
    args=parser.parse_args();sdk=args.sdk.resolve();java=args.java_home.resolve();work=args.work_dir.resolve();out=args.output_dir.resolve()
    work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    tool=sdk/'build-tools/35.0.0';platform=sdk/'platforms/android-35/android.jar'
    for required in [tool/'aapt2',tool/'d8',tool/'zipalign',tool/'apksigner',platform,java/'bin/javac',java/'bin/keytool']:
        if not required.is_file():raise FileNotFoundError(required)
    assets=work/'assets'
    if assets.exists():shutil.rmtree(assets)
    shutil.copytree(ROOT/'web',assets)
    for name in ('tax_engine.py','rules_2025.json','forms.py','official_forms.py','tax_extended.py','tax_credits.py','tax_additional.py','tax_longtail.py','tax_filing.py','presentation_schema.py','privacy_review.py'):
        if (ROOT/name).is_file():shutil.copy2(ROOT/name,assets/name)
    shutil.copytree(ROOT/'forms',assets/'forms',dirs_exist_ok=True)
    notices=assets/'third-party-notices';notices.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'LICENSE',notices/'Tax-Reborn-AGPL-3.0.txt')
    shutil.copytree(ROOT/'vendor',assets/'vendor-source',dirs_exist_ok=True)
    sources=list((ROOT/'android/src').rglob('*.java'));classes=work/'classes';classes.mkdir(exist_ok=True)
    unsigned=work/'unsigned.apk'
    run([tool/'aapt2','link','-o',unsigned,'--manifest',ROOT/'android/AndroidManifest.xml','-I',platform,'-A',assets,'--version-code','2026101404','--version-name','2026.10.14-preview.4','--min-sdk-version','26','--target-sdk-version','35'])
    run([java/'bin/javac','--release','8','-classpath',platform,'-d',classes,*sources])
    env=os.environ.copy();env['JAVA_HOME']=str(java);env['PATH']=str(java/'bin')+os.pathsep+env.get('PATH','')
    dex=work/'dex';dex.mkdir(exist_ok=True)
    run([tool/'d8','--lib',platform,'--min-api','26','--output',dex,*classes.rglob('*.class')],env=env)
    with zipfile.ZipFile(unsigned,'a',compression=zipfile.ZIP_DEFLATED) as package:package.write(dex/'classes.dex','classes.dex')
    aligned=work/'aligned.apk';run([tool/'zipalign','-f','4',unsigned,aligned])
    keystore=args.signing_keystore.resolve() if args.signing_keystore else work/'development-signing.jks'
    if args.signing_keystore and not keystore.is_file():parser.error('The explicitly selected signing keystore must already exist')
    if not keystore.exists():
        run([java/'bin/keytool','-genkeypair','-keystore',keystore,'-alias','tax-reborn-development','-keyalg','RSA','-keysize','2048','-validity','3650','-storepass','android','-keypass','android','-dname','CN=Tax Reborn Development, O=Local Preview, C=US'])
        keystore.chmod(0o600)
    apk=out/'Tax-Reborn-2026.10.14-preview.4-Android.apk'
    run([tool/'apksigner','sign','--ks',keystore,'--ks-key-alias','tax-reborn-development','--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned],env=env)
    checked=subprocess.run([str(tool/'apksigner'),'verify','--verbose','--print-certs',str(apk)],env=env,check=True,capture_output=True,text=True)
    (out/'android-signature-verification.txt').write_text(checked.stdout)
    manifest={'product':'Tax Reborn','project_number':'000002','version':'2026.10.14-preview.4','platform':'android','min_api':26,'target_api':35,'internet_permission':False,'signing':'private local development certificate; not a store release','file':apk.name,'bytes':apk.stat().st_size,'sha256':hashlib.file_digest(apk.open('rb'),'sha256').hexdigest(),'real_device_tested':False}
    (out/'build-manifest-android.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
