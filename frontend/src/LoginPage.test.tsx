// Tests mínimos de la UI (vitest + Testing Library).
// Corre con:  pnpm test        (vitest run)
// Mira con:   pnpm run test:watch

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./pages/LoginPage";

describe("LoginPage", () => {
  it("muestra el formulario de login", () => {
    render(<LoginPage onLoggedIn={() => {}} />);

    expect(screen.getByPlaceholderText("Correo electrónico")).toBeTruthy();
    expect(screen.getByPlaceholderText("Contraseña")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeTruthy();
  });

  it("pasa a modo registro y pide nombre", async () => {
    render(<LoginPage onLoggedIn={() => {}} />);

    // El tab "Crear cuenta" (queda desambiguado del submit por su posición)
    await userEvent.click(screen.getAllByRole("button", { name: "Crear cuenta" })[0]);

    expect(screen.getByPlaceholderText("Nombre (opcional)")).toBeTruthy();
    expect(screen.getByPlaceholderText("Contraseña (mín. 8)")).toBeTruthy();
  });

  it("muestra el enlace de recuperar contraseña", async () => {
    render(<LoginPage onLoggedIn={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "¿Olvidaste tu contraseña?" }));

    // El formulario de reset pide el correo está ahí y ofrece enviar el código
    expect(screen.getByPlaceholderText("Correo electrónico")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Enviar código" })).toBeTruthy();
  });

  it("permite desplegar el campo de servidor (instancia propia)", async () => {
    render(<LoginPage onLoggedIn={() => {}} />);

    // Colapsado por defecto
    expect(screen.queryByLabelText("Dirección del servidor")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Usar otra instancia (cambiar servidor)" }));

    expect(screen.getByLabelText("Dirección del servidor")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ocultar servidor" })).toBeTruthy();
  });

  it("rechaza una dirección de servidor sin http:// o https:// antes de mandar credenciales", async () => {
    const onLoggedIn = vi.fn();
    render(<LoginPage onLoggedIn={onLoggedIn} />);
    localStorage.removeItem("api_base");

    await userEvent.click(screen.getByRole("button", { name: "Usar otra instancia (cambiar servidor)" }));
    const serverInput = screen.getByLabelText("Dirección del servidor");
    await userEvent.clear(serverInput);
    await userEvent.type(serverInput, "ftp://mi-servidor");
    await userEvent.type(screen.getByPlaceholderText("Correo electrónico"), "a@b.co");
    await userEvent.type(screen.getByPlaceholderText("Contraseña"), "contrasenia1");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("La dirección debe empezar por http:// o https://")).toBeTruthy();
    expect(onLoggedIn).not.toHaveBeenCalled();
    // no se guardó nada inválido
    expect(localStorage.getItem("api_base")).toBeNull();
  });
});
