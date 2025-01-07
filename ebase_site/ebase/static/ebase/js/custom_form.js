function createAkt() {
	if (!url.searchParams.get('akt')) url.searchParams.append('akt', 'create');
	location.href = url;
}

const url = new URL(location.href);

var aktSpan = document.getElementsByClassName('akt-span')[0];
aktSpan.style.padding = '0px 7px 4px 4px';

var aktButton = document.getElementById('akt-create-btn');
aktButton.onclick = createAkt;

// Удаляем akt=create из get-параметров, чтобы лишний раз не вызывать метод создания акта в Django 
if (url.searchParams.get('akt')) {
	url.searchParams.delete('akt');	
	window.history.replaceState({}, document.title, url.toString());
} 
