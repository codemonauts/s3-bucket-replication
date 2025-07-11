{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    black
    python313Packages.pylint
    python313Packages.boto3
  ];
}
