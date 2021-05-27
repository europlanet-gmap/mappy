VERSION=$(shell git describe --tags --abbrev=0)

updateversion:
	sed -i  's/version=[.0-9]*/version=$(VERSION)/g' mappy/metadata.txt

updateinfo:
	cd scripts; \
	./render_info_to_html.py
	
deploy:
	cd mappy;\
	pb_tool deploy -y
	
package: updateversion updateinfo
	$(info    VERSION:  $(VERSION))
	cd mappy; \
	pb_tool zip; \
	cp zip_build/mappy.zip zip_build/mappy-${VERSION}.zip 
	

	

	
