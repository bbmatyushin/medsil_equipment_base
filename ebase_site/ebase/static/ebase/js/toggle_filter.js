(function($) {
    $(document).ready(function() {
        var $toggleButton = $('button.toggle-filter#hidden-filter-button');

        if (!$toggleButton.length) {
            return;
        }

        $toggleButton.on('click', function() {
            var html = document.documentElement;
            var isHidden = html.classList.toggle('changelist-filter-hidden');
            localStorage.setItem('django.admin.filterHidden', isHidden);
        });
    });
})(django.jQuery);
