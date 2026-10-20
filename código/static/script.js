// Botões de mostrar/esconder a palavra-passe
document.querySelectorAll(".mostrar-password").forEach(function (botao) {
    botao.addEventListener("click", function () {
        const input = botao.previousElementSibling;
        const aMostrar = input.type === "password";

        input.type = aMostrar ? "text" : "password";
        botao.setAttribute("aria-label", aMostrar ? "Esconder palavra-passe" : "Mostrar palavra-passe");
    });
});

// Confirmação da palavra-passe (só existe nas páginas com os dois campos)
const password = document.getElementById("password");
const confirmacao = document.getElementById("password_confirmacao");

if (password && confirmacao) {
    function verificarIguais() {
        if (confirmacao.value !== password.value) {
            confirmacao.setCustomValidity("As palavras-passe não coincidem.");
        } else {
            confirmacao.setCustomValidity("");
        }
    }

    password.addEventListener("input", verificarIguais);
    confirmacao.addEventListener("input", verificarIguais);
}
