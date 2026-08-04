{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    black
    python314Packages.pylint
    python314Packages.boto3
  ];
}
