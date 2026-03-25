fn main() {
    #[cfg(windows)]
    {
        use std::env;
        use winres::WindowsResource;

        // GitHub Actions 由来（無ければローカル向け既定値）
        let repo = env::var("CODEX_FORK_REPOSITORY")
            .unwrap_or_else(|_| "local-build".to_string());

        let tag = env::var("CODEX_FORK_TAG")
            .unwrap_or_else(|_| "dev".to_string());

        let product_name = format!("Codex (fork: {})", repo);
        let comments = format!(
            "Unofficial fork build. Repository: {}, Tag: {}",
            repo, tag
        );

        let product_version = tag
            .strip_prefix("rust-v")
            .unwrap_or(&tag)
            .to_string();

        let mut res = WindowsResource::new();

        res.set("ProductName", &product_name);
        res.set("FileDescription", "Codex CLI – Azure-compatible fork");
        res.set("CompanyName", &format!("{} (fork of openai/codex)", repo));
        res.set("OriginalFilename", "codex.exe");
        res.set("Comments", &comments);

        // 表示用バージョン（文字列）
        // res.set("ProductVersion", &product_version);
        // res.set("FileVersion", &product_version);

        res.compile().expect("Failed to compile Windows resources");
    }
}