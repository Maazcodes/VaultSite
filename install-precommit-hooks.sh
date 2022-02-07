#!/bin/bash
echo -e "#!/bin/bash\nblack ." >.git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
