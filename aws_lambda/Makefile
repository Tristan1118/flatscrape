all:
	pip install -r ../requirements.txt -t ./python
	find . -name "python_package.zip" -exec rm {} \;
	cp ../flatscrape/*.py python
	zip -r python_package.zip *
clean:
	rm -rf python
	rm -f python_package.zip
