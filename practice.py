import importlib.util, json, pathlib, sys
spec = importlib.util.spec_from_file_location('facts', pathlib.Path(__file__).with_name('practice-facts.py'))
facts = importlib.util.module_from_spec(spec); spec.loader.exec_module(facts)
level = sys.argv[1]
if level not in facts.GRADES: raise SystemExit('unknown grade')
print(json.dumps({'ok': True, **facts.practice(level)}))
