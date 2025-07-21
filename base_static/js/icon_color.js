function alterarImagemAoPassarMouse(nome_class_btn, nome_class_icon, nome_img1, nome_img2) {
    document.querySelectorAll(nome_class_btn).forEach(function(btn) {
        btn.addEventListener('mouseover', function() {
            btn.querySelectorAll(nome_class_icon).forEach(function(icon) {
                icon.src = nome_img1;
            });
        });

        btn.addEventListener('mouseout', function() {
            btn.querySelectorAll(nome_class_icon).forEach(function(icon) {
                icon.src = nome_img2;
            });
        });
    });
}