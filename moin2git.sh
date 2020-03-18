#!/bin/bash

# Other misc bash commands I had to run to migrate my MoinMoin wiki to Gollum
# Run within the repo:
sed -i -e 's/^\\#format rst//g' *.md
sed -i -e 's/^ \\#.*//g' *.md
sed -i -e 's/PythonOSOps/Python-OS-Ops/g' *.md
sed -i -e 's/GNUParallel/GNU-Parallel/g' *.md
sed -i -e 's/CWLMake/CWL-Make/g' *.md
sed -i -e 's/ITMistakes/IT-Mistakes/g' *.md
sed -i -e 's/MiscSysAdmin/Misc-SysAdmin/g' *.md
sed -i -e 's/AWSBackup/AWS-Backup/g' *.md
sed -i -e 's/HomeLab/Home-Lab/g' *.md
for category in $(grep -r --exclude-dir=.git "CategoryCategory" *.md | cut -d: -f1 | sed 's/.md//g'); do sed -i -e "s/"${category/-/}"/"${category}"/g" *.md; done
sed -i -e 's/\.\.\///g' *.md

# For finding tables that were not converted by the MoinMoin to rst converter:
grep -r --exclude-dir=.git "Table not converted"
