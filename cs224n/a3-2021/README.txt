Welcome to Assignment 3!

We'll be using PyTorch for this assignment. If you're not familiar with PyTorch, or if you would like to review some of the fundamentals of PyTorch, the PyTorch review session is posted on Canvas under Course Videos.  

If you want to continue using your cs224n environment from assignment 1 for this assignment, please make sure you have all the dependencies listed in local_env.yml. To do so, please run: 

# 1. Activate your old environment:

    conda activate cs224n

# 2. Install docopt

    conda install docopt

# 3. Install pytorch, torchvision, and tqdm

    conda install pytorch torchvision -c pytorch
    conda install -c anaconda tqdm


If you would like to instead create a new environment for this assignment, please run:

# 1. Create an environment with dependencies specified in local_env.yml (note that this can take some time depending on your laptop):
    
    conda env create -f local_env.yml

# 2. Activate the new environment:
    
    conda activate cs224n_a3
    

# To deactivate an active environment, use
    
    conda deactivate


(a) 
ROOT					I, parsed, this, sentence, correctly				Initial Configuration
ROOT, I					parsed, this, sentence, correctly				SHIFT
ROOT, I, parsed,			this, sentence, correctly					SHIFT
ROOT, parsed				this, sentence, correctly		I <- parsed		LEFT-ARC
ROOT, parsed, this			sentence, correctly						SHIFT
ROOT, parsed, this, sentence		correctly							SHIFT
ROOT, parsed, sentence			correctly				this <- sentence	LEFT-ARC
ROOT, parsed				correctly				parsed -> sentence	RIGHT-ARC
ROOT, parsed, correctly											SHIFT
ROOT, parsed									parsed -> correctly	RIGHT-ARC
ROOT										ROOT -> parsed		RIGHT-ARC

(b)
2n

(f)
i.	Error type: Verb Phrase Attachment Error
	Incorrect dependency: wedding -> fearing
	Correct dependency: heading -> fearing
ii.	Error type: Coordination Attachment Error
	Incorrect dependency: makes -> rescue
	Correct dependency: rush -> rescue
iii.	Error type: Preposition Phrase Attachment Error
	Incorrect dependency: named -> Midland
	Correct dependency: guy -> Midland
iv.	Error type: Modifier Attachment Error
	Incorrect dependency: elements -> most
	Correct dependency: crucial -> most
