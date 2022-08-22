VERSION=$(shell git describe --tags --abbrev=0)

updateversion:
	sed -i  's/version=[.a-zA-Z0-9]*/version=$(VERSION)/g' mappy/metadata.txt

updateinfo:
	cd scripts; \
	./render_info_to_html.py

clean:
	cd mappy;\
	rm -fr providers/__pycache__;\
	rm INFO.html;\
	rm resources.py;
	
deploy: clean updateinfo
	cd mappy;\
	pb_tool deploy -y
	
package: clean updateinfo
	$(info    VERSION:  $(VERSION))
	cd mappy; \
	pb_tool zip; \
	cp zip_build/mappy.zip zip_build/mappy-${VERSION}.zip 

tests:
	cd mappy/tests; \
	pytest -vs --order-dependencies

livedoc:
	poetry run sphinx-autobuild docs/source docs/build
	

	
