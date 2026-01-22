{
  description = "TerraVision - AI-Powered Terraform to Architecture Diagram Generator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        pythonPackages = python.pkgs;

        # Wrapper that provides 'terraform' command using opentofu
        terraformWrapper = pkgs.writeShellScriptBin "terraform" ''
          exec ${pkgs.opentofu}/bin/tofu "$@"
        '';

        # Override python-hcl2 to use version 4.3.0 as required by terravision
        python-hcl2 = pythonPackages.buildPythonPackage rec {
          pname = "python-hcl2";
          version = "4.3.0";
          pyproject = true;

          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-QeN+Kps9Ij2l6OvJnnK0DSMVCH6Wb0WPfqwTx4Mdm54=";
          };

          build-system = with pythonPackages; [ setuptools setuptools-scm ];

          dependencies = with pythonPackages; [
            lark
          ];

          doCheck = false;
        };

        terravision = pythonPackages.buildPythonApplication {
          pname = "terravision";
          version = "0.10.2";
          pyproject = true;

          src = ./.;

          build-system = [ pythonPackages.poetry-core ];

          dependencies = with pythonPackages; [
            click
            gitpython
            graphviz
            tqdm
            python-hcl2
            pyyaml
            debugpy
            ipaddr
            ollama
            requests
            typing-extensions
            tomli
          ];

          # Graphviz binary and terraform wrapper are needed at runtime
          makeWrapperArgs = [
            "--prefix" "PATH" ":" "${pkgs.lib.makeBinPath [ pkgs.graphviz terraformWrapper ]}"
          ];

          # Skip tests during build
          doCheck = false;

          meta = with pkgs.lib; {
            description = "Terraform Architecture Visualizer";
            homepage = "https://github.com/patrickchugh/terravision";
            license = licenses.agpl3Only;
            mainProgram = "terravision";
          };
        };

      in {
        packages = {
          default = terravision;
          terravision = terravision;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            terravision
            pkgs.graphviz
            terraformWrapper
            pkgs.git
          ];

          shellHook = ''
            echo "TerraVision development environment"
            echo "Run 'terravision --help' to get started"
          '';
        };
      }
    );
}
