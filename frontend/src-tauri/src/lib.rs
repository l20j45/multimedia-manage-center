// Código compartido de la app: usado por el binario de escritorio (main.rs)
// y por el shell nativo de Android/iOS (gen/<plataforma>).
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error al ejecutar la aplicación tauri");
}
