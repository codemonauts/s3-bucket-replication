format:
	black -l 120 -t py313 .

test:
	black -l 120 --check -t py313 .
	pylint lambda_function.py
