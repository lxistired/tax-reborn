#!/usr/bin/env python3
"""Build bundled native iOS on existing Xcode; never install SDKs or accept terms.

Default outputs are a Simulator app and an explicitly unsigned device app. An
unsigned device artifact cannot be installed on an iPhone. Optional signing uses
an already configured local team; no credentials or provisioning downloads occur.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = 'io.github.lxistired.taxreborn'
SOURCES = ['AppDelegate.swift', 'AssetRequest.swift', 'LoopbackAssetServer.swift', 'TaxViewController.swift']

def run(command, **kwargs):
    print('Running:', repr([str(item) for item in command]), flush=True)
    subprocess.run([str(item) for item in command], check=True, **kwargs)

def project_text():
    # Stable PBX identifiers, no third-party project generator dependency.
    objects = []
    def add(key, value): objects.append(f'\t\t{key} = {value};')
    ids = [f'A100000000000000000000{i:02X}' for i in range(len(SOURCES))]
    buildids = [f'A200000000000000000000{i:02X}' for i in range(len(SOURCES))]
    for key, build, filename in zip(ids, buildids, SOURCES):
        add(key, '{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = '+filename+'; sourceTree = "<group>";}')
        add(build, '{isa = PBXBuildFile; fileRef = '+key+';}')
    fixed = {
      'B10000000000000000000000': '{isa = PBXFileReference; lastKnownFileType = text.plist.xml; path = Info.plist; sourceTree = "<group>";}',
      'B10000000000000000000001': '{isa = PBXFileReference; lastKnownFileType = sourcecode.javascript; path = NativeBridge.js; sourceTree = "<group>";}',
      'B10000000000000000000002': '{isa = PBXFileReference; lastKnownFileType = text.xml; path = PrivacyInfo.xcprivacy; sourceTree = "<group>";}',
      'B10000000000000000000003': '{isa = PBXFileReference; lastKnownFileType = folder; path = GeneratedAssets/assets; sourceTree = "<group>";}',
      'B10000000000000000000004': '{isa = PBXFileReference; explicitFileType = wrapper.application; path = TaxReborn.app; sourceTree = BUILT_PRODUCTS_DIR;}',
      'B10000000000000000000005': '{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = TaxRebornUITests.swift; sourceTree = "<group>";}',
      'B10000000000000000000006': '{isa = PBXFileReference; explicitFileType = wrapper.cfbundle; path = TaxRebornUITests.xctest; sourceTree = BUILT_PRODUCTS_DIR;}',
      'B20000000000000000000001': '{isa = PBXBuildFile; fileRef = B10000000000000000000001;}',
      'B20000000000000000000002': '{isa = PBXBuildFile; fileRef = B10000000000000000000002;}',
      'B20000000000000000000003': '{isa = PBXBuildFile; fileRef = B10000000000000000000003;}',
      'B20000000000000000000005': '{isa = PBXBuildFile; fileRef = B10000000000000000000005;}',
      'C10000000000000000000000': '{isa = PBXGroup; children = (C10000000000000000000001, B10000000000000000000003, C10000000000000000000002, C10000000000000000000003); sourceTree = "<group>";}',
      'C10000000000000000000001': '{isa = PBXGroup; children = ('+', '.join(ids+['B10000000000000000000000','B10000000000000000000001','B10000000000000000000002'])+'); path = TaxReborn; sourceTree = "<group>";}',
      'C10000000000000000000002': '{isa = PBXGroup; children = (B10000000000000000000005); path = UITests; sourceTree = "<group>";}',
      'C10000000000000000000003': '{isa = PBXGroup; children = (B10000000000000000000004, B10000000000000000000006); name = Products; sourceTree = "<group>";}',
      'D10000000000000000000000': '{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ('+', '.join(buildids)+'); runOnlyForDeploymentPostprocessing = 0;}',
      'D10000000000000000000001': '{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (B20000000000000000000001, B20000000000000000000002, B20000000000000000000003); runOnlyForDeploymentPostprocessing = 0;}',
      'D10000000000000000000002': '{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;}',
      'D10000000000000000000003': '{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = (B20000000000000000000005); runOnlyForDeploymentPostprocessing = 0;}',
      'D10000000000000000000004': '{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;}',
      'D10000000000000000000005': '{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0;}',
      'E10000000000000000000000': '{isa = PBXNativeTarget; buildConfigurationList = F10000000000000000000001; buildPhases = (D10000000000000000000000,D10000000000000000000002,D10000000000000000000001); buildRules = (); dependencies = (); name = TaxReborn; productName = TaxReborn; productReference = B10000000000000000000004; productType = "com.apple.product-type.application";}',
      'E10000000000000000000001': '{isa = PBXNativeTarget; buildConfigurationList = F10000000000000000000002; buildPhases = (D10000000000000000000003,D10000000000000000000005,D10000000000000000000004); buildRules = (); dependencies = (E10000000000000000000003); name = TaxRebornUITests; productName = TaxRebornUITests; productReference = B10000000000000000000006; productType = "com.apple.product-type.bundle.ui-testing";}',
      'E10000000000000000000002': '{isa = PBXContainerItemProxy; containerPortal = FF0000000000000000000000; proxyType = 1; remoteGlobalIDString = E10000000000000000000000; remoteInfo = TaxReborn;}',
      'E10000000000000000000003': '{isa = PBXTargetDependency; target = E10000000000000000000000; targetProxy = E10000000000000000000002;}',
      'F10000000000000000000000': '{isa = XCConfigurationList; buildConfigurations = (F20000000000000000000000,F20000000000000000000001); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;}',
      'F10000000000000000000001': '{isa = XCConfigurationList; buildConfigurations = (F20000000000000000000002,F20000000000000000000003); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;}',
      'F10000000000000000000002': '{isa = XCConfigurationList; buildConfigurations = (F20000000000000000000004,F20000000000000000000005); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;}',
      'FF0000000000000000000000': '{isa = PBXProject; attributes = {LastUpgradeCheck = 1600; TargetAttributes = {E10000000000000000000001 = {TestTargetID = E10000000000000000000000;};};}; buildConfigurationList = F10000000000000000000000; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; knownRegions = (en,Base); mainGroup = C10000000000000000000000; productRefGroup = C10000000000000000000003; projectDirPath = ""; projectRoot = ""; targets = (E10000000000000000000000,E10000000000000000000001);}'
    }
    for key, value in fixed.items(): add(key,value)
    common = 'CLANG_ENABLE_MODULES = YES; SWIFT_VERSION = 5.0; IPHONEOS_DEPLOYMENT_TARGET = 16.4; SDKROOT = iphoneos; TARGETED_DEVICE_FAMILY = "1,2"; CODE_SIGN_STYLE = Automatic;'
    for i, name in enumerate(('Debug','Release')):
        add(f'F200000000000000000000{i:02X}', '{isa = XCBuildConfiguration; name = '+name+'; buildSettings = {'+common+' SWIFT_OPTIMIZATION_LEVEL = "'+('-Onone' if name=='Debug' else '-O')+'";};}')
        add(f'F200000000000000000000{i+2:02X}', '{isa = XCBuildConfiguration; name = '+name+'; buildSettings = {'+common+' PRODUCT_NAME = TaxReborn; PRODUCT_BUNDLE_IDENTIFIER = '+BUNDLE+'; INFOPLIST_FILE = TaxReborn/Info.plist; GENERATE_INFOPLIST_FILE = NO;};}')
        add(f'F200000000000000000000{i+4:02X}', '{isa = XCBuildConfiguration; name = '+name+'; buildSettings = {'+common+' PRODUCT_NAME = TaxRebornUITests; PRODUCT_BUNDLE_IDENTIFIER = '+BUNDLE+'.uitests; GENERATE_INFOPLIST_FILE = YES; TEST_TARGET_NAME = TaxReborn;};}')
    return '// !$*UTF8*$!\n{archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n'+'\n'.join(objects)+'\n}; rootObject = FF0000000000000000000000;}\n'

SCHEME = '''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1600" version="1.7">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="E10000000000000000000000" BuildableName="TaxReborn.app" BlueprintName="TaxReborn" ReferencedContainer="container:TaxReborn.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction>
<TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="YES"><Testables><TestableReference skipped="NO"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="E10000000000000000000001" BuildableName="TaxRebornUITests.xctest" BlueprintName="TaxRebornUITests" ReferencedContainer="container:TaxReborn.xcodeproj"/></TestableReference></Testables></TestAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="E10000000000000000000000" BuildableName="TaxReborn.app" BlueprintName="TaxReborn" ReferencedContainer="container:TaxReborn.xcodeproj"/></BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"/>
<AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
'''

def write_project(folder):
    project = folder/'TaxReborn.xcodeproj'
    schemes = project/'xcshareddata/xcschemes'
    schemes.mkdir(parents=True,exist_ok=True)
    (project/'project.pbxproj').write_text(project_text(),encoding='utf-8')
    (schemes/'TaxReborn.xcscheme').write_text(SCHEME,encoding='utf-8')
    return project

def prepare(work):
    project = work/'project'; project.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'ios/TaxReborn',project/'TaxReborn',dirs_exist_ok=True)
    shutil.copytree(ROOT/'ios/UITests',project/'UITests',dirs_exist_ok=True)
    assets = project/'GeneratedAssets/assets'
    if assets.exists(): shutil.rmtree(assets)
    shutil.copytree(ROOT/'web',assets,ignore=shutil.ignore_patterns('.*','__pycache__','*.pyc'))
    for name in ('tax_engine.py','tax_extended.py','tax_credits.py','tax_additional.py','rules_2025.json','forms.py'):
        shutil.copy2(ROOT/name,assets/name)
    shutil.copytree(ROOT/'forms',assets/'forms',ignore=shutil.ignore_patterns('.*','__pycache__','*.pyc'),dirs_exist_ok=True)
    shutil.copytree(ROOT/'vendor',assets/'vendor-source',ignore=shutil.ignore_patterns('.*','__pycache__','*.pyc'),dirs_exist_ok=True)
    (assets/'third-party-notices').mkdir(exist_ok=True)
    shutil.copy2(ROOT/'LICENSE',assets/'third-party-notices/Tax-Reborn-AGPL-3.0.txt')
    hashes = {path.relative_to(assets).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(assets.rglob('*')) if path.is_file()}
    (assets/'native-asset-manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
    return write_project(project), hashes

def zip_app(app, target):
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as package:
        for file in sorted(app.rglob('*')):
            if file.is_file(): package.write(file,Path(app.name)/file.relative_to(app))

def verify_bundled_assets(app, hashes):
    if not app.is_dir(): raise FileNotFoundError(app)
    for name, expected in hashes.items():
        file=app/'assets'/name
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=expected:
            raise ValueError('Native iOS bundled asset missing or changed: '+name)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-dir',type=Path,default=ROOT/'build/ios')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist/ios')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--run-ui-tests',action='store_true')
    parser.add_argument('--skip-device',action='store_true')
    parser.add_argument('--team-id',help='Use only an already configured local development team. No provisioning download.')
    args = parser.parse_args()
    work,out=args.work_dir.resolve(),args.output_dir.resolve()
    work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    project,hashes=prepare(work)
    manifest={'product':'Tax Reborn','project_number':'000002','version':(ROOT/'VERSION').read_text().strip(),
              'platform':'ios','deployment_target':'16.4','stable_origin':'http://127.0.0.1:18786',
              'asset_count':len(hashes),'source_prepared':True,'simulator_built':False,
              'simulator_gui_tested':False,'device_built':False,'device_signed':False,'bundled_assets_verified':False,
              'real_device_tested':False,'artifacts':[]}
    receipt=out/'build-manifest-ios.json'
    def save(): receipt.write_text(json.dumps(manifest,indent=2)+'\n')
    save()
    if args.prepare_only:
        print('Prepared:',project); return 0
    if sys.platform!='darwin': parser.error('Native iOS builds require macOS and existing full Xcode.')
    # A missing SDK is a real prerequisite; do not download it or accept terms.
    subprocess.run(['xcrun','--sdk','iphonesimulator','--show-sdk-path'],check=True,capture_output=True,text=True)
    derived=work/'DerivedData'
    common=['xcodebuild','-project',project,'-scheme','TaxReborn','-derivedDataPath',derived]
    run(common+['-configuration','Release','-sdk','iphonesimulator','-destination','generic/platform=iOS Simulator','CODE_SIGNING_ALLOWED=NO','build'])
    simapp=derived/'Build/Products/Release-iphonesimulator/TaxReborn.app'
    verify_bundled_assets(simapp,hashes)
    with (simapp/'Info.plist').open('rb') as stream: info=plistlib.load(stream)
    if info['CFBundleIdentifier']!=BUNDLE: raise ValueError('iOS bundle identifier mismatch')
    version=manifest['version']
    simzip=out/f'Tax-Reborn-{version}-iOS-Simulator.app.zip';zip_app(simapp,simzip)
    manifest.update(simulator_built=True,bundled_assets_verified=True)
    manifest['artifacts'].append({'file':simzip.name,'bytes':simzip.stat().st_size,'sha256':hashlib.sha256(simzip.read_bytes()).hexdigest(),'installable_on_iphone':False})
    save()
    if not args.skip_device:
        signing=['CODE_SIGNING_ALLOWED=NO'] if not args.team_id else ['DEVELOPMENT_TEAM='+args.team_id,'CODE_SIGN_STYLE=Automatic']
        run(common+['-configuration','Release','-sdk','iphoneos','-destination','generic/platform=iOS']+signing+['build'])
        device=derived/'Build/Products/Release-iphoneos/TaxReborn.app'
        verify_bundled_assets(device,hashes)
        if args.team_id:
            run(['codesign','--verify','--strict',device])
            signed=subprocess.run(['codesign','--display','--verbose=4',device],check=True,capture_output=True,text=True)
            if 'TeamIdentifier='+args.team_id not in signed.stderr or not (device/'embedded.mobileprovision').is_file():
                raise ValueError('Device build lacks the requested team signature/provisioning profile')
        devicezip=out/f'Tax-Reborn-{version}-iOS-'+('Development-Signed' if args.team_id else 'Unsigned-Device')+'.app.zip'
        zip_app(device,devicezip)
        manifest.update(device_built=True,device_signed=bool(args.team_id))
        manifest['artifacts'].append({'file':devicezip.name,'bytes':devicezip.stat().st_size,'sha256':hashlib.sha256(devicezip.read_bytes()).hexdigest(),'installable_on_iphone':bool(args.team_id),'requires_matching_device_provisioning':True})
        save()
    if args.run_ui_tests:
        runtimes=json.loads(subprocess.check_output(['xcrun','simctl','list','runtimes','-j']))['runtimes']
        runtime=next(iter(sorted((item for item in runtimes if item.get('isAvailable') and 'iOS' in item.get('name','')),key=lambda item:tuple(int(part) for part in item['version'].split('.')),reverse=True)),None)
        types=json.loads(subprocess.check_output(['xcrun','simctl','list','devicetypes','-j']))['devicetypes']
        phones=[item for item in types if item.get('productFamily')=='iPhone' or item['name'].startswith('iPhone')]
        # simctl validates the selected device/runtime pair; try newest installed types.
        if not runtime or not phones: raise RuntimeError('No existing iOS Simulator runtime/iPhone type. No SDK installation was attempted.')
        udid=None
        for phone in reversed(phones):
            attempt=subprocess.run(['xcrun','simctl','create','Tax Reborn CI',phone['identifier'],runtime['identifier']],capture_output=True,text=True)
            if attempt.returncode==0: udid=attempt.stdout.strip();break
        if not udid: raise RuntimeError('No compatible existing iPhone Simulator type.')
        result=out/'ios-ui-smoke.xcresult'
        if result.exists(): shutil.rmtree(result)
        try:
            run(['xcrun','simctl','boot',udid]);run(['xcrun','simctl','bootstatus',udid,'-b'])
            run(common+['-configuration','Debug','-destination','platform=iOS Simulator,id='+udid,'-resultBundlePath',result,'CODE_SIGNING_ALLOWED=NO','test'],timeout=900)
            run(['xcrun','simctl','io',udid,'screenshot',out/'ios-native-gui.png'])
            manifest['simulator_gui_tested']=True;save()
        finally:
            subprocess.run(['xcrun','simctl','shutdown',udid],capture_output=True)
            subprocess.run(['xcrun','simctl','delete',udid],capture_output=True)
    print(json.dumps(manifest,indent=2),flush=True)
    return 0

if __name__=='__main__': raise SystemExit(main())
