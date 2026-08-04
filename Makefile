format:
	black -l 120 -t py314 .

test:
	black -l 120 --check -t py314 .
	pylint lambda_function.py
