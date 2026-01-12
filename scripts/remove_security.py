import re
import glob

# Files to process
files = glob.glob('app/api/v1/endpoints/*.py')

for filepath in files:
    if filepath.endswith('__init__.py'):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Remove the import
    content = re.sub(r'from app\.core\.security import .*?get_current_user.*?\n', '', content)
    
    # Remove current_user parameter from function signatures - handle all variations
    content = re.sub(r',\s*current_user:\s*Dict\s*=\s*Depends\(get_current_user\)', '', content)
    content = re.sub(r'current_user:\s*Dict\s*=\s*Depends\(get_current_user\),', '', content)
    
    # Replace references to current_user["sub"] or current_user['sub']
    content = re.sub(r'current_user\["sub"\]', 'None', content)
    content = re.sub(r"current_user\['sub'\]", 'None', content)
    
    # Replace filter conditions
    content = re.sub(r'\.filter\(\w+\.user_id\s*==\s*current_user\["sub"\]\)', '', content)
    content = re.sub(r"\.filter\(\w+\.user_id\s*==\s*current_user\['sub'\]\)", '', content)
    
    if original != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {filepath}')
    else:
        print(f'No changes needed in {filepath}')
