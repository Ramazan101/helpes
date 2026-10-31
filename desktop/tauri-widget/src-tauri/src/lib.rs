use serde::Serialize;
use std::env;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, WebviewWindow,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use tauri_plugin_opener::OpenerExt;

#[derive(Serialize)]
pub struct DesktopInfo {
    pub os: String,
    pub session_type: String,
    pub is_wayland: bool,
    pub backend_url: String,
}

#[tauri::command]
fn get_desktop_info() -> DesktopInfo {
    let session_type = env::var("XDG_SESSION_TYPE").unwrap_or_else(|_| "unknown".to_string());
    let is_wayland =
        env::var("WAYLAND_DISPLAY").is_ok() || session_type.to_lowercase() == "wayland";
    let backend_url =
        env::var("HELPDESK_BACKEND_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());

    DesktopInfo {
        os: env::consts::OS.to_string(),
        session_type,
        is_wayland,
        backend_url,
    }
}

#[tauri::command]
fn toggle_always_on_top(window: WebviewWindow) -> Result<bool, String> {
    let current = window.is_always_on_top().map_err(|e| e.to_string())?;
    let new_state = !current;
    window
        .set_always_on_top(new_state)
        .map_err(|e| e.to_string())?;
    Ok(new_state)
}

#[tauri::command]
fn open_browser_url(app: AppHandle, url: String) -> Result<(), String> {
    app.opener()
        .open_url(&url, None::<&str>)
        .map_err(|e| e.to_string())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            get_desktop_info,
            toggle_always_on_top,
            open_browser_url,
        ])
        .setup(|app| {
            // 1. Формирование системного трея и контекстного меню
            let show_item = MenuItem::with_id(app, "show", "Показать окно", true, None::<&str>)?;
            let hide_item = MenuItem::with_id(app, "hide", "Скрыть окно", true, None::<&str>)?;
            let queue_item = MenuItem::with_id(
                app,
                "queue",
                "Очередь заявок (в браузере)",
                true,
                None::<&str>,
            )?;
            let ticket_item = MenuItem::with_id(
                app,
                "ticket",
                "Подать заявку (в браузере)",
                true,
                None::<&str>,
            )?;
            let separator1 = PredefinedMenuItem::separator(app)?;
            let separator2 = PredefinedMenuItem::separator(app)?;
            let quit_item = MenuItem::with_id(app, "quit", "Выход", true, None::<&str>)?;

            let tray_menu = Menu::with_items(
                app,
                &[
                    &show_item,
                    &hide_item,
                    &separator1,
                    &queue_item,
                    &ticket_item,
                    &separator2,
                    &quit_item,
                ],
            )?;

            let icon = app.default_window_icon().cloned().unwrap();
            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .tooltip("Help Desk «Кыргыз Алтын»")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.hide();
                        }
                    }
                    "queue" => {
                        let backend = env::var("HELPDESK_BACKEND_URL")
                            .unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());
                        let _ = app
                            .opener()
                            .open_url(format!("{}/tech/queue/", backend), None::<&str>);
                    }
                    "ticket" => {
                        let backend = env::var("HELPDESK_BACKEND_URL")
                            .unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());
                        let _ = app.opener().open_url(format!("{}/", backend), None::<&str>);
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("main") {
                            if win.is_visible().unwrap_or(false) {
                                let _ = win.hide();
                            } else {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                    }
                })
                .build(app)?;

            // 2. Регистрация глобальной горячей клавиши Ctrl+Shift+H
            if let Ok(shortcut) = "Ctrl+Shift+H".parse::<Shortcut>() {
                let _ = app
                    .global_shortcut()
                    .on_shortcut(shortcut, |app, _shortcut, event| {
                        if event.state() == ShortcutState::Pressed {
                            if let Some(win) = app.get_webview_window("main") {
                                if win.is_visible().unwrap_or(false) {
                                    let _ = win.hide();
                                } else {
                                    let _ = win.show();
                                    let _ = win.set_focus();
                                }
                            }
                        }
                    });
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Нажатие на крестик скрывает окно в трей вместо завершения процесса
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running helpes widget");
}
