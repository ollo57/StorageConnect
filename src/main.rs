use axum::extract::path;
use axum::{Router, routing::get};
use std::net::SocketAddr;
pub use tokio::net::TcpListener;
use tower_http::services::{ServeDir};
use tower_http::services::{ServeFile};
use std::collections::HashMap;
use std::sync::LazyLock;
use std::env;

async fn hello_world() -> &'static str {
    "Hello world!"
}



#[tokio::main]
async fn main() {
let mut BASE_DIR     = 	std::env::current_dir();
const BASE_UPLOAD_FOLDER:&path = Path::new("uploads");
static FRIEND_KEY:&str = "";
let MAX_FILE_SIZE_ = 2000;
const APPROVED_DEVICES_FILE:&path = Path::new("approved_devices.json");
const SETTINGS_FILE:&path = Path::new("settings.json");

     let router = Router::new()
        .route_service("/", ServeDir::new("static")
          .not_found_service(ServeFile::new("templates/index.html")
        )
    );




    let addr = SocketAddr::from(([127,0,0,1], 8000));
    let tcp = TcpListener::bind(&addr).await.unwrap();

    axum::serve(tcp, router).await.unwrap();
}